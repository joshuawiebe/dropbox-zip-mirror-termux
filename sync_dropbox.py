#!/usr/bin/env python3
"""
sync_dropbox.py

Core script:
- Downloads Dropbox public ZIP (?dl=1) to DOWNLOAD_PATH
- Extracts ZIP to a temporary directory
- Compares files in temp vs TARGET_DIR using SHA256
- Copies new files; updates changed files (and archives old versions if configured)
- Deletes the ZIP and temporary extraction folder
- Writes a concise log and prints summary in real-time with progress bars

Config is read from: ./.dropbox_mirror.env (repo-local) or ~/.dropbox_mirror.env (fallback).
If config missing and running interactively, script asks for setup.
Designed for Termux + venv + Termux:Widget trigger (~/.shortcuts/run-sync.sh).

New feature in this version:
- Dynamic progress bars for download, extraction, and sync
- Percentage info and ETA for download
- Improved logging with human-readable timestamps
- Summary table at the end of sync
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
C0_RE = re.compile(r'[\x00-\x1F\x7F]')  # control chars

def strip_ansi_and_control(s: str) -> str:
    """Remove ANSI escape sequences and control characters from a string."""
    if not isinstance(s, str):
        return s
    s2 = ANSI_RE.sub('', s)
    s2 = C0_RE.sub('', s2)
    return s2.strip()

def read_env(path=ENV_PATH):
    """Read environment variables from config file and sanitize values"""
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
    """Interactive prompt with optional default"""
    if default:
        res = input(f"{prompt} [{default}]: ").strip()
        return res if res else default
    return input(f"{prompt}: ").strip()

def timestamp(fmt="%Y-%m-%d %H:%M:%S"):
    """Return human-readable timestamp string"""
    return datetime.now().strftime(fmt)

def ensure_dir(p):
    """Ensure directory exists"""
    Path(p).mkdir(parents=True, exist_ok=True)

def sha256_file(path):
    """Compute SHA256 hash of file"""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"Error hashing file {path}: {e}", flush=True)
        return None

def sha256_fileobj(fp):
    """Compute SHA256 hash of open file object"""
    h = hashlib.sha256()
    try:
        for chunk in iter(lambda: fp.read(1024*1024), b""):
            h.update(chunk)
        fp.seek(0)
        return h.hexdigest()
    except Exception as e:
        print(f"Error hashing file object: {e}", flush=True)
        return None

def is_interactive():
    """Check if script runs interactively (not widget)"""
    return sys.stdin.isatty() and os.environ.get("TERMUX_WIDGET") != "1"

def expand_path(path_str):
    """Expand ~ and environment variables in path"""
    return str(Path(path_str).expanduser().resolve())

def validate_url(u: str) -> bool:
    """Basic URL validation using urllib.parse"""
    try:
        parsed = urlparse(u)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False

def print_progress_bar(current, total, prefix="", length=40, speed=None, eta=None):
    """Print a dynamic progress bar in terminal"""
    percent = current / total if total else 0
    filled_length = int(length * percent)
    bar = "█" * filled_length + "-" * (length - filled_length)
    extra = ""
    if speed is not None:
        extra += f" | {speed/1024:.1f} KB/s"
    if eta is not None:
        extra += f" | ETA {int(eta)}s"
    print(f"\r{prefix} |{bar}| {percent*100:6.2f}% ({current}/{total}){extra}", end="", flush=True)
    if current >= total:
        print()

def safe_log_write(log_fp, text):
    """Try to write to log_fp, fallback to stdout if fails"""
    try:
        if log_fp:
            log_fp.write(text)
            log_fp.flush()
    except Exception:
        try:
            print("LOG-ERROR: failed to write log. Outputting instead:", flush=True)
            print(text, flush=True)
        except Exception:
            pass

# ------------------ Core functions ------------------
def download_zip(url, out_path):
    """Download Dropbox ZIP file with progress bar, speed and ETA"""
    out_path = Path(expand_path(out_path))
    ensure_dir(out_path.parent)
    safe_url = strip_ansi_and_control(url)
    print(f"📥 Downloading ZIP from {safe_url} -> {out_path}", flush=True)

    if not validate_url(safe_url):
        raise ValueError(f"Invalid URL after sanitizing: {safe_url}")

    try:
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
        print("✅ Download finished.", flush=True)
        return out_path
    except Exception as e:
        raise RuntimeError(str(e))

def extract_zip(zip_path, dest_dir):
    """Extract ZIP safely (no path traversal) with progress"""
    dest_dir = Path(expand_path(dest_dir))
    ensure_dir(dest_dir)
    print(f"📦 Extracting ZIP {zip_path} -> {dest_dir}", flush=True)

    try:
        with zipfile.ZipFile(str(zip_path), "r") as z:
            safe_members = []
            for zi in z.infolist():
                if ".." in Path(zi.filename).parts or zi.filename.startswith("/"):
                    print(f"[!] Skipping suspicious entry: {zi.filename}", flush=True)
                    continue
                safe_members.append(zi)
            total_files = len(safe_members)
            for idx, member in enumerate(safe_members, 1):
                z.extract(member, path=str(dest_dir))
                print_progress_bar(idx, total_files, prefix="Extracting")
        print(f"✅ Extracted {len(safe_members)} files safely.", flush=True)
        return dest_dir
    except Exception as e:
        print(f"[!] Extraction failed: {e}", flush=True)
        raise

def sync_from_dir(src_dir, target_dir, keep_versions=True, dry_run=False, log_fp=None):
    """Sync files with progress, percent, logging, and summary"""
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
            if not dry_run:
                ensure_dir(dest_file.parent)
            if dest_file.exists():
                new_hash = sha256_file(src_file)
                old_hash = sha256_file(dest_file)
                if new_hash and old_hash and new_hash == old_hash:
                    skipped += 1
                    msg = f"⏭ SKIP: {rel}"
                    safe_log_write(log_fp, f"{timestamp()} {msg}\n")
                else:
                    if dry_run:
                        updated += 1
                        msg = f"✏️ DRY-UPDATE: {rel}"
                    else:
                        if keep_versions:
                            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                            archive_path = versions_dir / f"{rel}.{ts}"
                            ensure_dir(archive_path.parent)
                            shutil.move(str(dest_file), str(archive_path))
                            arch_msg = f"🗄 ARCHIVE: {rel} -> .old_versions/{rel}.{ts}"
                            safe_log_write(log_fp, f"{timestamp()} {arch_msg}\n")
                        shutil.copy2(src_file, dest_file)
                        updated += 1
                        msg = f"🔄 UPDATE: {rel}"
                    safe_log_write(log_fp, f"{timestamp()} {msg}\n")
            else:
                if dry_run:
                    copied += 1
                    msg = f"➕ DRY-COPY: {rel}"
                else:
                    shutil.copy2(src_file, dest_file)
                    copied += 1
                    msg = f"✅ COPY: {rel}"
                safe_log_write(log_fp, f"{timestamp()} {msg}\n")
        except Exception as e:
            errors += 1
            msg = f"[!] ERROR processing {rel}: {e}"
            safe_log_write(log_fp, f"{timestamp()} {msg}\n")

        print_progress_bar(counter, total_files, prefix="Syncing")

    summary = {
        "total": total_files,
        "copied": copied,
        "skipped": skipped,
        "updated": updated,
        "errors": errors,
    }
    print("📊 Sync Summary:", flush=True)
    for k, v in summary.items():
        print(f"   {k:8}: {v}", flush=True)
    return summary

# ------------------ Main ------------------
def main():
    print("🟢 Starting Dropbox ZIP Mirror sync", flush=True)
    print(f"📄 Config path: {ENV_PATH}", flush=True)

    cfg = read_env()

    # Interactive config if missing
    if not cfg.get("DROPBOX_URL") and is_interactive():
        print("💡 Interactive setup (config missing).", flush=True)
        cfg["DROPBOX_URL"] = ask("Dropbox public URL (?dl=1)")
        cfg["DOWNLOAD_PATH"] = ask("Local ZIP path", str(script_dir / "dropbox_latest.zip"))
        cfg["TARGET_DIR"] = ask("Target directory", str(script_dir / "DropboxMirror"))
        cfg["KEEP_VERSIONS"] = ask("Keep old versions? (yes/no)", "yes")
        cfg["DRY_RUN"] = ask("Dry run? (yes/no)", "no")
        cfg["LOG_PATH"] = ask("Log file path", str(script_dir / "sync.log"))
        try:
            env_text = "\n".join(f"{k}={v}" for k, v in cfg.items())
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write(env_text + "\n")
            print(f"✅ Wrote config to {ENV_PATH}", flush=True)
        except Exception as e:
            print(f"[!] Could not save config: {e}", flush=True)

    # Config defaults
    url = strip_ansi_and_control(cfg.get("DROPBOX_URL", ""))
    download_path = expand_path(cfg.get("DOWNLOAD_PATH", str(script_dir / "dropbox_latest.zip")))
    target_dir = expand_path(cfg.get("TARGET_DIR", str(script_dir / "DropboxMirror")))
    keep_versions = strip_ansi_and_control(cfg.get("KEEP_VERSIONS", "yes")).lower().startswith("y")
    dry_run = strip_ansi_and_control(cfg.get("DRY_RUN", "no")).lower() in ("1","true","yes","y")
    log_path = expand_path(cfg.get("LOG_PATH", str(script_dir / "sync.log")))

    if "--dry-run" in sys.argv:
        dry_run = True
        print("⚡ Dry run mode enabled via CLI", flush=True)

    if not url or "dropbox.com" not in url:
        print("[!] ERROR: DROPBOX_URL missing or invalid", flush=True)
        return 1

    url = re.sub(r'(\?|&)+dl=[01]', '', url).rstrip("&?") + ("&dl=1" if "?" in url else "?dl=1")
    url = strip_ansi_and_control(url)
    if not validate_url(url):
        print(f"[!] ERROR: DROPBOX_URL invalid after sanitizing: {url}", flush=True)
        return 1

    ensure_dir(target_dir)
    ensure_dir(Path(log_path).parent)

    print(f"🌐 URL: {url}", flush=True)
    print(f"📂 Target: {target_dir}", flush=True)
    print(f"💭 Dry run: {dry_run}", flush=True)

    try:
        with open(log_path, "a", encoding="utf-8") as log_fp:
            safe_log_write(log_fp, f"{timestamp()} === RUN START ===\n")
            safe_log_write(log_fp, f"{timestamp()} URL: {url}\n")
            safe_log_write(log_fp, f"{timestamp()} Target: {target_dir}\n")
            safe_log_write(log_fp, f"{timestamp()} Dry run: {dry_run}\n")

            try:
                zip_path = download_zip(url, download_path)
                safe_log_write(log_fp, f"{timestamp()} Downloaded to: {zip_path}\n")
            except Exception as e:
                msg = f"Download failed: {e}"
                print(f"[!] {msg}", flush=True)
                safe_log_write(log_fp, f"{timestamp()} ERROR: {msg}\n")
                return 1

            tmpdir = Path(tempfile.mkdtemp(prefix="dbx_sync_"))
            try:
                extract_zip(zip_path, tmpdir)
                safe_log_write(log_fp, f"{timestamp()} Extracted to: {tmpdir}\n")
            except Exception as e:
                msg = f"Extraction failed: {e}"
                print(f"[!] {msg}", flush=True)
                safe_log_write(log_fp, f"{timestamp()} ERROR: {msg}\n")
                shutil.rmtree(tmpdir, ignore_errors=True)
                return 2

            try:
                print(f"🔄 Syncing files...", flush=True)
                summary = sync_from_dir(tmpdir, target_dir, keep_versions, dry_run, log_fp)
                safe_log_write(log_fp, f"{timestamp()} SYNC COMPLETE: {summary}\n")
            except Exception as e:
                msg = f"Sync failed: {e}"
                print(f"[!] {msg}", flush=True)
                safe_log_write(log_fp, f"{timestamp()} ERROR: {msg}\n")

            try:
                if Path(zip_path).exists():
                    Path(zip_path).unlink()
                    safe_log_write(log_fp, f"{timestamp()} Deleted ZIP: {zip_path}\n")
                shutil.rmtree(tmpdir)
                safe_log_write(log_fp, f"{timestamp()} Deleted temp dir: {tmpdir}\n")
            except Exception as e:
                safe_log_write(log_fp, f"{timestamp()} WARNING: Cleanup failed: {e}\n")

            safe_log_write(log_fp, f"{timestamp()} === RUN END ===\n")
    except Exception as e:
        print(f"[!] ERROR: Could not write to log {log_path}: {e}", flush=True)
        return 3

    print("🎉 Dropbox Mirror sync finished successfully!", flush=True)
    return 0

if __name__ == "__main__":
    try:
        status = main()
        sys.exit(status)
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user", flush=True)
        sys.exit(130)
    except Exception as e:
        print(f"[!] Unexpected error: {e}", flush=True)
        sys.exit(1)
