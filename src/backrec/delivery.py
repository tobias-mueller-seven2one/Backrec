"""What reaches the target folder after a recording - the contract with the
next tool in the chain.

`unique_destination` and the verified copy are moved unchanged out of
`main.pyw` (lines 96-104 and 730-752): a name collision never overwrites, and a
copy counts as done only once its size matches the original.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .logging_setup import get_logger

log = get_logger(__name__)


def unique_destination(dst: Path) -> Path:
    """A free name in the target folder; an existing file is never overwritten."""
    if not dst.exists():
        return dst
    stem, suffix, counter = dst.stem, dst.suffix, 1
    while True:
        candidate = dst.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def copy_verified(source: Path, target_dir: Path) -> Path | None:
    """Copies `source` into `target_dir` and checks the copy by its size.

    Returns the destination, or None if the copy failed or came out different.
    The original stays where it is - the recording folder keeps everything, so a
    failed delivery can be repeated.
    """
    try:
        original_size = source.stat().st_size
    except OSError:
        log.error("[KOPIE] Quelldatei nicht lesbar: %s", source, exc_info=True)
        return None

    destination = unique_destination(target_dir / source.name)
    log.info("[KOPIE] Kopiere nach: %s", destination)

    try:
        shutil.copy2(str(source), str(destination))
    except OSError:
        log.error("[KOPIE] Kopieren nach '%s' fehlgeschlagen", destination, exc_info=True)
        return None

    if destination.exists() and destination.stat().st_size == original_size:
        log.info("[KOPIE] Kopie verifiziert, Groesse identisch (%d Bytes)", original_size)
        return destination

    log.error(
        "[KOPIE] Groessenabweichung nach Kopie! Original=%d, Kopie=%s",
        original_size,
        destination.stat().st_size if destination.exists() else "fehlt",
    )
    return None
