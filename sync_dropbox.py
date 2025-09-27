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

Config is read from: ~/.dropbox_mirror.env (key=value).
If config missing, script asks interactively (only on manual CLI use).
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

ENV_PATH = Path.home() / ".dropbox_mirror.env"

# ---------------- helpers ----------------
def read_env(path=ENV_PATH):
    d = {}
    if not Path(path).exists():
        return d
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            d[k.strip()] = v.strip()
    return d

def ask(prompt, default=None):
    if default:
        res = input(f"{prompt} [{default}]: ").strip()
        return res if res else default
    return input(f"{prompt}: ").strip()

def timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def ensure_dir(p):
    Path(p).mkdir(parents=True, exist_ok=True)

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def sha256_fileobj(fp):
    h = hashlib.sha256()
    for chunk in iter(lambda: fp.read(1024*1024), b""):
        h.update(chunk)
    try:
        fp.seek(0)
    except Exception:
        pass
    return h.hexdigest()

def safe_join(base, *parts):
    # Prevent path traversal by resolving and ensuring base is prefix.
    base = Path(base).resolve()
    target = base.joinpath(*parts).resolve()
    if not str(target).startswith(str(base)):
        raise Exception("Path traversal detected")
    return target

# ---------------- core functions ----------------
def download_zip(url, out_path):
    out_path = Path(out_path)
    ensure_dir(out_path.parent)
    print(f"[+] Downloading ZIP from {url} -> {out_path}")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print("[+] Download finished.")
    return out_path

def extract_zip(zip_path, dest_dir):
    print(f"[+] Extracting ZIP {zip_path} -> {dest_dir}")
    with zipfile.ZipFile(str(zip_path), "r") as z:
        # protect path traversal
        bad = False
        for zi in z.infolist():
            if ".." in Path(zi.filename).parts:
                print(f"[!] Skipping suspicious entry: {zi.filename}")
                bad = True
        # normal extract
        z.extractall(path=str(dest_dir))
    print("[+] Extract complete.")
    return dest_dir

def sync_from_dir(src_dir, target_dir, keep_versions=True, dry_run=False, log_fp=None):
    src_dir = Path(src_dir)
    target_dir = Path(target_dir)
    versions_dir = target_dir.joinpath(".old_versions")
    if keep_versions:
        ensure_dir(versions_dir)

    total = copied = skipped = updated = 0
    for root, _, files in os.walk(src_dir):
        for fn in files:
            rel = Path(root).joinpath(fn).relative_to(src_dir)
            total += 1
            src_file = src_dir.joinpath(rel)
            dest_file = target_dir.joinpath(rel)
            try:
                ensure_dir(dest_file.parent)
                if dest_file.exists():
                    # compare hashes
                    with open(src_file, "rb") as sf:
                        new_hash = sha256_fileobj(sf)
                    old_hash = sha256_file(dest_file)
                    if new_hash == old_hash:
                        skipped += 1
                        msg = f"SKIP: {rel} (unchanged)"
                        print(msg)
                        if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
                        continue
                    else:
                        # changed -> archive old if requested, then copy
                        if dry_run:
                            updated += 1
                            msg = f"DRY-UPDATE: {rel} (would archive and replace)"
                            print(msg)
                            if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
                        else:
                            if keep_versions:
                                ts = timestamp()
                                archive_path = versions_dir.joinpath(f"{rel}.{ts}")
                                ensure_dir(archive_path.parent)
                                shutil.move(str(dest_file), str(archive_path))
                                msg = f"ARCHIVE: {rel} -> {archive_path.relative_to(target_dir)}"
                                print(msg)
                                if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
                            shutil.copy2(src_file, dest_file)
                            updated += 1
                            msg = f"UPDATE: {rel}"
                            print(msg)
                            if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
                else:
                    # new file
                    if dry_run:
                        copied += 1
                        msg = f"DRY-COPY: {rel} (would copy new file)"
                        print(msg)
                        if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
                    else:
                        ensure_dir(dest_file.parent)
                        shutil.copy2(src_file, dest_file)
                        copied += 1
                        msg = f"COPY: {rel}"
                        print(msg)
                        if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
            except Exception as e:
                msg = f"ERROR processing {rel}: {e}"
                print(msg)
                if log_fp: log_fp.write(f"{timestamp()} {msg}\n")
    return {"total": total, "copied": copied, "skipped": skipped, "updated": updated}

# ---------------- main ----------------
def main():
    cfg = read_env()
    # interactive fallbacks if env missing (only for CLI)
    if not cfg.get("DROPBOX_URL"):
        print("Interactive setup (no ~/.dropbox_mirror.env found).")
        cfg["DROPBOX_URL"] = ask("Dropbox public URL (?dl=1):")
        cfg["DOWNLOAD_PATH"] = ask("Local ZIP download path", str(Path.home() / "storage" / "shared" / "Download" / "dropbox_latest.zip"))
        cfg["TARGET_DIR"] = ask("Target directory", str(Path.home() / "storage" / "shared" / "DropboxMirror"))
        cfg["KEEP_VERSIONS"] = ask("Keep old versions? (yes/no)", "yes")
        cfg["DRY_RUN"] = ask("Dry run? (yes/no)", "no")
        # save config back
        env_text = "\n".join(f"{k}={v}" for k, v in cfg.items())
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write(env_text + "\n")
        print(f"Wrote config to {ENV_PATH}")

    url = cfg.get("DROPBOX_URL")
    download_path = cfg.get("DOWNLOAD_PATH", str(Path.home() / "storage" / "shared" / "Download" / "dropbox_latest.zip"))
    target_dir = cfg.get("TARGET_DIR", str(Path.home() / "storage" / "shared" / "DropboxMirror"))
    keep_versions = cfg.get("KEEP_VERSIONS", "yes").lower().startswith("y")
    dry_run = cfg.get("DRY_RUN", "no").lower().startswith("y")
    log_path = cfg.get("LOG_PATH", str(Path.home() / "sync_dropbox.log"))

    # allow CLI flags: --dry-run
    if len(sys.argv) > 1:
        if "--dry-run" in sys.argv:
            dry_run = True

    ensure_dir(Path(target_dir))
    ensure_dir(Path(log_path).parent)

    with open(log_path, "a", encoding="utf-8") as log_fp:
        log_fp.write(f"{timestamp()} RUN start url={url} target={target_dir} dry_run={dry_run}\n")
        try:
            zip_path = download_zip(url, download_path)
        except Exception as e:
            msg = f"Download failed: {e}"
            print(msg)
            log_fp.write(f"{timestamp()} ERROR {msg}\n")
            return 1

        tmpdir = Path(tempfile.mkdtemp(prefix="dbx_sync_"))
        try:
            extract_zip(zip_path, tmpdir)
        except Exception as e:
            msg = f"Extraction failed: {e}"
            print(msg)
            log_fp.write(f"{timestamp()} ERROR {msg}\n")
            # cleanup
            try:
                shutil.rmtree(tmpdir)
            except Exception:
                pass
            return 2

        try:
            summary = sync_from_dir(tmpdir, target_dir, keep_versions=keep_versions, dry_run=dry_run, log_fp=log_fp)
            log_fp.write(f"{timestamp()} SUMMARY {summary}\n")
            print("Summary:", summary)
        except Exception as e:
            msg = f"Sync failed: {e}"
            print(msg)
            log_fp.write(f"{timestamp()} ERROR {msg}\n")
            # continue to cleanup
        # cleanup
        try:
            if Path(zip_path).exists():
                Path(zip_path).unlink()
            shutil.rmtree(tmpdir)
        except Exception as e:
            log_fp.write(f"{timestamp()} WARNING cleanup issue: {e}\n")

        log_fp.write(f"{timestamp()} RUN end\n")

    # Attempt a Termux notification if available
    try:
        # termux-notification command exists on device if termux-api installed
        if shutil.which("termux-notification"):
            os.system(f'termux-notification --title "Dropbox Mirror" --content "Sync finished. See {log_path}" --priority high')
    except Exception:
        pass

    return 0

if __name__ == "__main__":
    status = main()
    sys.exit(status)