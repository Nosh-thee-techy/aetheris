"""Copy media and CSV downloads next to the Vite build for Vercel."""

from __future__ import annotations

import shutil
from pathlib import Path

WEB = Path(__file__).resolve().parent
SPA = WEB / "spa"


def copy_dir(name: str) -> None:
    src = WEB / name
    dest = SPA / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def main() -> None:
    if not (SPA / "index.html").exists():
        raise SystemExit("web/spa/index.html missing. Build the Vite app first.")
    copy_dir("media")
    copy_dir("data")


if __name__ == "__main__":
    main()
