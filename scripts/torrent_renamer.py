#!/usr/bin/env python3
"""
Torrent Blackhole renamer for Readarr + WebTranslatorr.

WebTranslatorr returns the actual book file.  Readarr saves it with
a .torrent extension.  This script detects the real file type from
the magic bytes and renames it to the correct extension so Readarr's
Drone Factory can import it.

Usage:
    docker run --rm -v /downloads/blackhole:/watch -v /downloads/import:/import \\
        python:3.11-slim sh -c "python /script.py"

Or run natively:
    python3 torrent_renamer.py /downloads/blackhole /downloads/import
"""
import os
import sys
import time
import shutil
from pathlib import Path

MAGIC = {
    b"PK\x03\x04": ".epub",        # ZIP-based (EPUB)
    b"PK\x03\x04": ".epub",        # same magic, EPUB is more likely for books
    b"%PDF": ".pdf",
    b"BOOKMOBI": ".mobi",
}


def detect_extension(filepath: str) -> str | None:
    """Detect file extension from magic bytes."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(16)
        for magic, ext in MAGIC.items():
            if header.startswith(magic):
                return ext
    except Exception:
        pass
    return None


def watch(watch_dir: str, output_dir: str, interval: int = 3):
    """Watch directory for new .torrent files and rename them."""
    watch_path = Path(watch_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    seen = set()
    print(f"[renamer] Watching {watch_dir} → {output_dir}")

    while True:
        for f in sorted(watch_path.glob("*.torrent")):
            fname = str(f)
            if fname in seen or f.stat().st_size == 0:
                continue
            # Wait for file to finish writing
            size1 = f.stat().st_size
            time.sleep(1)
            if f.stat().st_size != size1:
                time.sleep(1)
            if f.stat().st_size == 0:
                continue
            seen.add(fname)

            ext = detect_extension(fname) or ".bin"
            dest = output_path / f"{f.stem}{ext}"
            shutil.move(fname, str(dest))
            print(f"[renamer] {f.name} → {dest.name}")

        time.sleep(interval)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    wd = sys.argv[1]
    od = sys.argv[2] if len(sys.argv) > 2 else wd
    watch(wd, od)
