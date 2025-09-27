#!/usr/bin/env python3
"""
sync_dropbox.py

Core script:
- Downloads Dropbox public ZIP (?dl=1) to DOWNLOAD_PATH
- Extracts ZIP to a temporary directory
- Compares files in temp vs TARGET_DIR using SHA256
- Copies new files; updates changed files (and archives old versions if configured)
- Deletes the ZIP and temporary extraction folder
- Writes a concise log and prints summary

Config is read from: ./.dropbox_mirror.env (repo-local) or ~/.dropbox_mirror.env (fallback).
If config missing and running interactively, script asks for setup.
Designed for Termux + venv + Termux:Widget trigger (~/.shortcuts/run-sync.sh).
"""

import os
import sys
import shutil
import hashlib
import zipfile
import tempfile
import time
from pathlib import Path
from datetime import datetime
import requests

# Try repo-local config first, then home directory
script_dir = Path(__file__).parent
ENV_PATH = script_dir / ".dropbox_mirror.env"
if not ENV_PATH.exists():
    ENV_PATH = Path.home() / ".dropbox_mirror.env"

# ---------------- helpers ----------------
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
        print(f"Warning: Could not read config file {path}: {e}")
    return d

def ask(prompt, default=None):
    """Interactive prompt with optional default"""
    if default:
        res = input(f"{prompt} [{default}]: ").strip()
        return res if res else default
    return input(f"{prompt}: ").strip()

def timestamp():
    """Generate timestamp string"""
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def ensure_dir(p):
    """Create directory if it doesn't exist"""
    Path(p).mkdir(parents=True, exist_ok=True)

def sha256_file(path):
    """Calculate SHA256 hash of file"""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"Error hashing file {path}: {e}")
        return None

def sha256_fileobj(fp):
    """Calculate SHA256 hash of file object"""
    h = hashlib.sha256()
    try:
        for chunk in iter(lambda: fp.read(1024*1024), b""):
            h.update(chunk)
        fp.seek(0)
        return h.hexdigest()
    except Exception as e:
        print(f"Error hashing file object: {e}")
        return None

def is_interactive():
    """Check if running in interactive mode"""
    return sys.stdin.isatty() and os.environ.get('TERMUX_WIDGET') != '1'

def expand_path(path_str):
    """Expand ~ and environment variables in paths"""
    return str(Path(path_str).expanduser().resolve())

# ---------------- core functions ----------------
def download_zip(url, out_path):
    """Download ZIP file from URL"""
    out_path = Path(expand_path(out_path))
    ensure_dir(out_path.parent)
    print(f"[+] Downloading ZIP from {url} -> {out_path}")
    
    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            
            with open(out_path, "wb") as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r[+] Downloaded {downloaded}/{total_size} bytes ({percent:.1f}%)", end="")
            
            print("\n[+] Download finished.")
            return out_path
    except Exception as e:
        print(f"[!] Download failed: {e}")
        raise

def extract_zip(zip_path, dest_dir):
    """Extract ZIP file safely, preventing path traversal"""
    print(f"[+] Extracting ZIP {zip_path} -> {dest_dir}")
    
    try:
        with zipfile.ZipFile(str(zip_path), "r") as z:
            # Filter out dangerous entries
            safe_members = []
            for zi in z.infolist():
                # Check for path traversal
                if ".." in Path(zi.filename).parts or zi.filename.startswith("/"):
                    print(f"[!] Skipping suspicious entry: {zi.filename}")
                    continue
                safe_members.append(zi)
            
            # Extract only safe members
            for member in safe_members:
                z.extract(member, path=str(dest_dir))
                
        print(f"[+] Extracted {len(safe_members)} files safely.")
        return dest_dir
    except Exception as e:
        print(f"[!] Extraction failed: {e}")
        raise

def sync_from_dir(src_dir, target_dir, keep_versions=True, dry_run=False, log_fp=None):
    """Sync files from source to target directory"""
    src_dir = Path(expand_path(src_dir))
    target_dir = Path(expand_path(target_dir))
    versions_dir = target_dir.joinpath(".old_versions")
    
    if keep_versions and not dry_run:
        ensure_dir(versions_dir)

    total = copied = skipped = updated = errors = 0
    
    for root, _, files in os.walk(src_dir):
        for fn in files:
            rel = Path(root).joinpath(fn).relative_to(src_dir)
            total += 1
            src_file = src_dir.joinpath(rel)
            dest_file = target_dir.joinpath(rel)
            
            try:
                if not dry_run:
                    ensure_dir(dest_file.parent)
                
                if dest_file.exists():
                    # Compare hashes
                    with open(src_file, "rb") as sf:
                        new_hash = sha256_fileobj(sf)
                    old_hash = sha256_file(dest_file)
                    
                    if new_hash and old_hash and new_hash == old_hash:
                        skipped += 1
                        msg = f"SKIP: {rel} (unchanged)"
                        print(msg)
                        if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
                        continue
                    else:
                        # Changed file - archive old if requested, then copy
                        if dry_run:
                            updated += 1
                            msg = f"DRY-UPDATE: {rel} (would archive and replace)"
                        else:
                            if keep_versions:
                                ts = timestamp()
                                archive_path = versions_dir.joinpath(f"{rel}.{ts}")
                                ensure_dir(archive_path.parent)
                                shutil.move(str(dest_file), str(archive_path))
                                arch_msg = f"ARCHIVE: {rel} -> .old_versions/{rel}.{ts}"
                                print(arch_msg)
                                if log_fp: log_fp.write(f"{timestamp()} {arch_msg}\n")
                            
                            shutil.copy2(src_file, dest_file)
                            updated += 1
                            msg = f"UPDATE: {rel}"
                        
                        print(msg)
                        if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
                else:
                    # New file
                    if dry_run:
                        copied += 1
                        msg = f"DRY-COPY: {rel} (would copy new file)"
                    else:
                        ensure_dir(dest_file.parent)
                        shutil.copy2(src_file, dest_file)
                        copied += 1
                        msg = f"COPY: {rel}"
                    
                    print(msg)
                    if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
                        
            except Exception as e:
                errors += 1
                msg = f"ERROR processing {rel}: {e}"
                print(msg)
                if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
    
    return {"total": total, "copied": copied, "skipped": skipped, "updated": updated, "errors": errors}

# ---------------- main ----------------
def main():
    """Main function"""
    print(f"[+] Starting Dropbox Mirror sync")
    print(f"[+] Config path: {ENV_PATH}")
    
    cfg = read_env()
    
    # Check if we have required config
    if not cfg.get("DROPBOX_URL"):
        if not is_interactive():
            print("ERROR: No config found and running non-interactively")
            print(f"Create config file at: {ENV_PATH}")
            print("Required: DROPBOX_URL=https://www.dropbox.com/s/XXXXX/yourfolder.zip?dl=1")
            return 1
        
        print("Interactive setup (no config found).")
        cfg["DROPBOX_URL"] = ask("Dropbox public URL (?dl=1)")
        if not cfg["DROPBOX_URL"]:
            print("ERROR: Dropbox URL is required")
            return 1
            
        cfg["DOWNLOAD_PATH"] = ask("Local ZIP download path", 
                                   str(script_dir / "dropbox_latest.zip"))
        cfg["TARGET_DIR"] = ask("Target directory", 
                               str(script_dir / "DropboxMirror"))
        cfg["KEEP_VERSIONS"] = ask("Keep old versions? (yes/no)", "yes")
        cfg["DRY_RUN"] = ask("Dry run? (yes/no)", "no")
        cfg["LOG_PATH"] = ask("Log file path", 
                             str(script_dir / "sync_dropbox.log"))
        
        # Save config
        try:
            env_text = "\n".join(f"{k}={v}" for k, v in cfg.items())
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write(env_text + "\n")
            print(f"Wrote config to {ENV_PATH}")
        except Exception as e:
            print(f"Warning: Could not save config: {e}")

    # Get configuration with defaults
    url = cfg.get("DROPBOX_URL")
    download_path = cfg.get("DOWNLOAD_PATH", str(script_dir / "dropbox_latest.zip"))
    target_dir = cfg.get("TARGET_DIR", str(script_dir / "DropboxMirror"))
    keep_versions = cfg.get("KEEP_VERSIONS", "yes").lower().startswith("y")
    dry_run = cfg.get("DRY_RUN", "no").lower().startswith("y")
    log_path = cfg.get("LOG_PATH", str(script_dir / "sync_dropbox.log"))

    # Allow CLI flags: --dry-run
    if len(sys.argv) > 1:
        if "--dry-run" in sys.argv:
            dry_run = True
            print("[+] Dry run mode enabled via CLI flag")

    # Validate URL
    if not url or not url.endswith("?dl=1"):
        print("ERROR: DROPBOX_URL must end with '?dl=1'")
        return 1

    # Expand paths
    download_path = expand_path(download_path)
    target_dir = expand_path(target_dir)
    log_path = expand_path(log_path)
    
    print(f"[+] URL: {url}")
    print(f"[+] Target: {target_dir}")
    print(f"[+] Dry run: {dry_run}")

    # Ensure directories exist
    try:
        ensure_dir(Path(target_dir))
        ensure_dir(Path(log_path).parent)
    except Exception as e:
        print(f"ERROR: Could not create directories: {e}")
        return 1

    # Main sync process with logging
    try:
        with open(log_path, "a", encoding="utf-8") as log_fp:
            log_fp.write(f"{timestamp()} === RUN START ===\n")
            log_fp.write(f"{timestamp()} URL: {url}\n")
            log_fp.write(f"{timestamp()} Target: {target_dir}\n") 
            log_fp.write(f"{timestamp()} Dry run: {dry_run}\n")
            
            # Download
            try:
                zip_path = download_zip(url, download_path)
                log_fp.write(f"{timestamp()} Downloaded to: {zip_path}\n")
            except Exception as e:
                msg = f"Download failed: {e}"
                print(f"[!] {msg}")
                log_fp.write(f"{timestamp()} ERROR: {msg}\n")
                return 1

            # Extract
            tmpdir = Path(tempfile.mkdtemp(prefix="dbx_sync_"))
            try:
                extract_zip(zip_path, tmpdir)
                log_fp.write(f"{timestamp()} Extracted to: {tmpdir}\n")
            except Exception as e:
                msg = f"Extraction failed: {e}"
                print(f"[!] {msg}")
                log_fp.write(f"{timestamp()} ERROR: {msg}\n")
                try:
                    shutil.rmtree(tmpdir)
                except Exception:
                    pass
                return 2

            # Sync
            try:
                print(f"[+] Syncing files from {tmpdir} to {target_dir}")
                summary = sync_from_dir(tmpdir, target_dir, 
                                      keep_versions=keep_versions, 
                                      dry_run=dry_run, log_fp=log_fp)
                log_fp.write(f"{timestamp()} SYNC COMPLETE: {summary}\n")
                print(f"[+] Sync complete: {summary}")
            except Exception as e:
                msg = f"Sync failed: {e}"
                print(f"[!] {msg}")
                log_fp.write(f"{timestamp()} ERROR: {msg}\n")
            
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
        print(f"ERROR: Could not write to log file {log_path}: {e}")
        return 3

    # Send notification if available
    try:
        if shutil.which("termux-notification"):
            os.system(f'termux-notification --title "Dropbox Mirror" --content "Sync finished. Check {log_path}" --priority high')
    except Exception:
        pass

    print("[+] Dropbox Mirror sync completed successfully")
    return 0

if __name__ == "__main__":
    try:
        status = main()
        sys.exit(status)
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        sys.exit(1)