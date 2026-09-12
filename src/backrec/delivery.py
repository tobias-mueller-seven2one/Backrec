"""What reaches the target folder after a recording - the contract with the
next tool in the chain.

`unique_destination` and the verified copy are moved unchanged out of
`main.pyw` (lines 96-104 and 730-752): a name collision never overwrites, and a
copy counts as done only once its size matches the original.

What did change is the failure case (design D8). The retired `_fallback_copy_raw`
(`main.pyw:719-728`) copied both raw takes into the target folder when mixing
failed. Generous for Backrec alone - nothing is lost - and a broken contract for
everyone downstream: the next tool reads every file in that folder and
transcribes **the same conversation twice**, once from the microphone and once
from the system side. The mistake then surfaces two tools later, at a place
where nobody thinks of ffmpeg. So nothing goes into the target folder unless it
is the one mixed file, and the takes stay where they were recorded, ready for a
second attempt once the cause is fixed.

`finish` takes the mixing function as an argument so that every failure - a
missing mixer, an error during mixing, an unusable result, a copy that came out
different - is reachable from a test without arranging it on the machine.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .logging_setup import get_logger
from .merge import merge_audio_files, is_usable

log = get_logger(__name__)

MergeFunction = Callable[[Path, Path, Path], "tuple[bool, str]"]

# What ffmpeg's absence looks like coming out of `merge_audio_files`. Matched
# rather than guessed at, because "not callable" and "ended with an error" are
# two different next steps for the reader.
MISSING_MIXER_MARKER = "ffmpeg nicht gefunden"


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


@dataclass(frozen=True)
class Outcome:
    """The result of finishing a recording, in the shapes the window needs.

    `status` is the one line that fits into a 280 px wide window, `cause` and
    `whereabouts` are the two sentences of the visible failure message. All
    three exist because the status line alone cannot carry a folder path, and
    the specification asks for the whereabouts of the takes to be named in the
    window and not only in the log.
    """

    ok: bool
    destination: Path | None = None
    status: str = ""
    cause: str = ""
    whereabouts: str = ""


def _failed(cause: str, recording_dir: Path, status: str) -> Outcome:
    whereabouts = f"Beide Spuren liegen weiterhin in {recording_dir}."
    log.error("[ABSCHLUSS] %s %s", cause, whereabouts)
    return Outcome(ok=False, status=status, cause=cause, whereabouts=whereabouts)


def finish(
    mic_path: Path | None,
    system_path: Path | None,
    timestamp: str,
    recording_dir: Path,
    target_dir: Path,
    *,
    merge_fn: MergeFunction = merge_audio_files,
) -> Outcome:
    """Mixes both takes and hands the result over. Nothing else ever travels.

    Every early return leaves the recording folder exactly as it was, which is
    what makes a second attempt after fixing the cause possible at all.
    """
    if not is_usable(mic_path):
        return _failed(
            "Die Spur des Mikrofons fehlt oder ist zu kurz.",
            recording_dir,
            "no result: mic track",
        )

    if not is_usable(system_path):
        return _failed(
            "Die Spur des Systemtons fehlt oder ist zu kurz.",
            recording_dir,
            "no result: system track",
        )

    assert mic_path is not None and system_path is not None  # noqa: S101 - narrowed by is_usable

    merged_path = recording_dir / f"{timestamp}.wav"
    mixed, detail = merge_fn(mic_path, system_path, merged_path)

    if not mixed:
        if MISSING_MIXER_MARKER in detail:
            return _failed(
                "Das Programm zum Zusammenmischen ist nicht aufrufbar.",
                recording_dir,
                "no result: mixer missing",
            )
        return _failed(
            "Das Zusammenmischen endete mit einem Fehler.",
            recording_dir,
            "no result: mixing failed",
        )

    if not is_usable(merged_path):
        return _failed(
            "Beim Zusammenmischen ist keine brauchbare Datei entstanden.",
            recording_dir,
            "no result: empty file",
        )

    destination = copy_verified(merged_path, target_dir)
    if destination is None:
        return _failed(
            "Die Übernahme in den Zielordner hat nicht geklappt.",
            recording_dir,
            "no result: copy failed",
        )

    log.info("[ABSCHLUSS] Ergebnis abgelegt: %s", destination)
    return Outcome(ok=True, destination=destination, status="saved (merged)")


def discard(*takes: Path | None) -> bool:
    """Removes the takes of a discarded recording. Says whether all of them went.

    Deliberately the only operation of this module that touches the target
    folder not at all: discarding is a decision about the recording folder, and
    a delivery that already happened is none of its business.
    """
    removed_all = True

    for take in takes:
        if take is None:
            continue
        try:
            take.unlink(missing_ok=True)
            log.info("[VERWERFEN] Rohdatei verworfen: %s", take)
        except OSError:
            removed_all = False
            log.error("[VERWERFEN] Rohdatei liess sich nicht loeschen: %s", take, exc_info=True)

    return removed_all
