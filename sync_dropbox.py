#!/usr/bin/env python3
"""
sync_dropbox.py

Core script:
- Downloads Dropbox public ZIP (?dl=1) to DOWNLOAD_PATH
- Extracts ZIP to a temporary directory
- Compares files in temp vs TARGET_DIR using SHA256
- Copies new files; updates changed files (and archives old versions if configured)
- Deletes the ZIP and temporary extraction folder
- Writes a concise log and prints summary in real-time

Config is read from: ./.dropbox_mirror.env (repo-local) or ~/.dropbox_mirror.env (fallback).
If config missing and running interactively, script asks for setup.
Designed for Termux + venv + Termux:Widget trigger (~/.shortcuts/run-sync.sh) or Termux Job Scheduler.
"""

import os
import sys
import shutil
import hashlib
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime
import requests
import time

# ------------------ Config paths ------------------
script_dir = Path(__file__).parent
ENV_PATH = script_dir / ".dropbox_mirror.env"
if not ENV_PATH.exists():
    ENV_PATH = Path.home() / ".dropbox_mirror.env"

# ------------------ Helpers ------------------
def read_env(path=ENV_PATH):
    """Read environment variables from config file"""
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
                d[k.strip()] = v.strip()
    except Exception as e:
        print(f"Warning: Could not read config file {path}: {e}", flush=True)
    return d

def ask(prompt, default=None):
    """Interactive prompt with optional default"""
    if default:
        res = input(f"{prompt} [{default}]: ").strip()
        return res if res else default
    return input(f"{prompt}: ").strip()

def timestamp():
    """Return timestamp string"""
    return datetime.now().strftime("%Y%m%d-%H%M%S")

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

# ------------------ Core functions ------------------
def download_zip(url, out_path):
    """Download Dropbox ZIP file"""
    out_path = Path(expand_path(out_path))
    ensure_dir(out_path.parent)
    print(f"📥 Downloading ZIP from {url} -> {out_path}", flush=True)

    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r📥 Downloaded {downloaded}/{total_size} bytes ({percent:.1f}%)", end="", flush=True)
        print("\n✅ Download finished.", flush=True)
        return out_path
    except Exception as e:
        print(f"[!] Download failed: {e}", flush=True)
        raise

def extract_zip(zip_path, dest_dir):
    """Extract ZIP safely (no path traversal)"""
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
            for member in safe_members:
                z.extract(member, path=str(dest_dir))
        print(f"✅ Extracted {len(safe_members)} files safely.", flush=True)
        return dest_dir
    except Exception as e:
        print(f"[!] Extraction failed: {e}", flush=True)
        raise

def sync_from_dir(src_dir, target_dir, keep_versions=True, dry_run=False, log_fp=None):
    """Sync files from source to target with SHA256 comparison"""
    src_dir = Path(expand_path(src_dir))
    target_dir = Path(expand_path(target_dir))
    versions_dir = target_dir / ".old_versions"

    if keep_versions and not dry_run:
        ensure_dir(versions_dir)

    total_files = sum(len(files) for _, _, files in os.walk(src_dir))
    counter = 0
    copied = skipped = updated = errors = 0

    for root, _, files in os.walk(src_dir):
        for fn in files:
            counter += 1
            rel = Path(root).joinpath(fn).relative_to(src_dir)
            src_file = src_dir / rel
            dest_file = target_dir / rel
            try:
                if not dry_run:
                    ensure_dir(dest_file.parent)
                if dest_file.exists():
                    # Compare hashes
                    new_hash = sha256_file(src_file)
                    old_hash = sha256_file(dest_file)
                    if new_hash and old_hash and new_hash == old_hash:
                        skipped += 1
                        msg = f"⏭ SKIP: {rel} ({counter}/{total_files}) unchanged"
                        print(msg, flush=True)
                        if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
                        continue
                    else:
                        # Update
                        if dry_run:
                            updated += 1
                            msg = f"✏️ DRY-UPDATE: {rel} ({counter}/{total_files}) would replace"
                        else:
                            if keep_versions:
                                ts = timestamp()
                                archive_path = versions_dir / f"{rel}.{ts}"
                                ensure_dir(archive_path.parent)
                                shutil.move(str(dest_file), str(archive_path))
                                arch_msg = f"🗄 ARCHIVE: {rel} -> .old_versions/{rel}.{ts}"
                                print(arch_msg, flush=True)
                                if log_fp: log_fp.write(f"{timestamp()} {arch_msg}\n")
                            shutil.copy2(src_file, dest_file)
                            updated += 1
                            msg = f"🔄 UPDATE: {rel} ({counter}/{total_files})"
                        print(msg, flush=True)
                        if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
                else:
                    # New file
                    if dry_run:
                        copied += 1
                        msg = f"➕ DRY-COPY: {rel} ({counter}/{total_files}) would copy"
                    else:
                        shutil.copy2(src_file, dest_file)
                        copied += 1
                        msg = f"✅ COPY: {rel} ({counter}/{total_files})"
                    print(msg, flush=True)
                    if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
            except Exception as e:
                errors += 1
                msg = f"[!] ERROR processing {rel}: {e}"
                print(msg, flush=True)
                if log_fp: log_fp.write(f"{timestamp()} {msg}\n")

    summary = {
        "total": total_files,
        "copied": copied,
        "skipped": skipped,
        "updated": updated,
        "errors": errors,
    }
    return summary

# ------------------ Main ------------------
def main():
    print("🟢 Starting Dropbox ZIP Mirror sync", flush=True)
    print(f"📄 Config path: {ENV_PATH}", flush=True)

    cfg = read_env()

    # Detect Termux Job Scheduler
    RUNNING_JOB = os.environ.get("TERMUX_JOB_ID") is not None

    # Interactive config if missing
    if not cfg.get("DROPBOX_URL"):
        if RUNNING_JOB:
            print(f"[!] ERROR: Config missing and running under Termux Job Scheduler (job id {os.environ.get('TERMUX_JOB_ID')})", flush=True)
            return 1
        elif not is_interactive():
            print("[!] ERROR: Config missing and running non-interactively", flush=True)
            return 1

        print("💡 Interactive setup (config missing).", flush=True)
        cfg["DROPBOX_URL"] = ask("Dropbox public URL (?dl=1)")
        cfg["DOWNLOAD_PATH"] = ask("Local ZIP path", str(script_dir / "dropbox_latest.zip"))
        cfg["TARGET_DIR"] = ask("Target directory", str(script_dir / "DropboxMirror"))
        cfg["KEEP_VERSIONS"] = ask("Keep old versions? (yes/no)", "yes")
        cfg["DRY_RUN"] = ask("Dry run? (yes/no)", "no")
        cfg["LOG_PATH"] = ask("Log file path", str(script_dir / "sync.log"))
        # Save config
        try:
            env_text = "\n".join(f"{k}={v}" for k, v in cfg.items())
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write(env_text + "\n")
            print(f"✅ Wrote config to {ENV_PATH}", flush=True)
        except Exception as e:
            print(f"[!] Could not save config: {e}", flush=True)

    # Config defaults
    url = cfg.get("DROPBOX_URL")
    download_path = cfg.get("DOWNLOAD_PATH", str(script_dir / "dropbox_latest.zip"))
    target_dir = cfg.get("TARGET_DIR", str(script_dir / "DropboxMirror"))
    keep_versions = cfg.get("KEEP_VERSIONS", "yes").lower().startswith("y")
    dry_run = cfg.get("DRY_RUN", "no").lower().startswith("y")
    log_path = cfg.get("LOG_PATH", str(script_dir / "sync.log"))

    # CLI flags
    if "--dry-run" in sys.argv:
        dry_run = True
        print("⚡ Dry run mode enabled via CLI", flush=True)

    # Normalize URL
    if not url or "dropbox.com" not in url:
        print("[!] ERROR: DROPBOX_URL missing or invalid", flush=True)
        return 1
    url = url.replace("&dl=0", "").replace("&dl=1", "").replace("?dl=0", "").replace("?dl=1", "")
    url = url + ("&dl=1" if "?" in url else "?dl=1")

    # Expand paths
    download_path = expand_path(download_path)
    target_dir = expand_path(target_dir)
    log_path = expand_path(log_path)
    ensure_dir(Path(target_dir))
    ensure_dir(Path(log_path).parent)

    print(f"🌐 URL: {url}", flush=True)
    print(f"📂 Target: {target_dir}", flush=True)
    print(f"💭 Dry run: {dry_run}", flush=True)

    try:
        with open(log_path, "a", encoding="utf-8") as log_fp:
            log_fp.write(f"{timestamp()} === RUN START ===\n")
            log_fp.write(f"{timestamp()} URL: {url}\n")
            log_fp.write(f"{timestamp()} Target: {target_dir}\n")
            log_fp.write(f"{timestamp()} Dry run: {dry_run}\n")

            # Download
            zip_path = download_zip(url, download_path)
            log_fp.write(f"{timestamp()} Downloaded to: {zip_path}\n")

            # Extract
            tmpdir = Path(tempfile.mkdtemp(prefix="dbx_sync_"))
            extract_zip(zip_path, tmpdir)
            log_fp.write(f"{timestamp()} Extracted to: {tmpdir}\n")

            # Sync
            print(f"🔄 Syncing files...", flush=True)
            summary = sync_from_dir(tmpdir, target_dir, keep_versions, dry_run, log_fp)
            log_fp.write(f"{timestamp()} SYNC COMPLETE: {summary}\n")
            print(f"✅ Sync complete: {summary}", flush=True)

            # Cleanup
            try:
                if Path(zip_path).exists():
                    Path(zip_path).unlink()
                    log_fp.write(f"{timestamp()} Deleted ZIP: {zip_path}\n")
                shutil.rmtree(tmpdir)
                log_fp.write(f"{timestamp()} Deleted temp dir: {tmpdir}\n")
            except Exception as e:
                log_fp.write(f"{timestamp()} WARNING: Cleanup failed: {e}\n")

            log_fp.write(f"{timestamp()} === RUN END ===\n")
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
