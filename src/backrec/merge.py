"""The ffmpeg call that turns the two raw takes into one file.

Moved unchanged out of `main.pyw` (lines 46-48 and 107-136). The filter chain is
character-identical to the one that has been in use: both sources are resampled
to 44.1 kHz mono and mixed with `normalize=0`, so neither of them is turned down
because the other one is loud.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .logging_setup import get_logger

log = get_logger(__name__)

FFMPEG_EXE = "ffmpeg"
MERGE_SAMPLERATE = 44100
MERGE_CHANNELS = 1
MERGE_TIMEOUT_SECONDS = 120

# Below this a WAV carries no usable audio - it is a header and little else.
MIN_USABLE_BYTES = 1024


def merge_audio_files(mic_path: Path, system_path: Path, output_path: Path) -> tuple[bool, str]:
    """FFmpeg amix: duration=longest, dropout_transition=0, weights=1 1:normalize=0."""
    cmd = [
        FFMPEG_EXE, "-y",
        "-i", str(mic_path),
        "-i", str(system_path),
        "-filter_complex",
        "[0:a]aresample=44100,aformat=channel_layouts=mono[a0];"
        "[1:a]aresample=44100,aformat=channel_layouts=mono[a1];"
        "[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0:weights=1 1:normalize=0",
        "-ar", str(MERGE_SAMPLERATE), "-ac", str(MERGE_CHANNELS),
        str(output_path)
    ]
    log.info(f"[MERGE] FFmpeg-Befehl: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=MERGE_TIMEOUT_SECONDS)
    except FileNotFoundError:
        log.error("[MERGE] ffmpeg nicht gefunden (nicht installiert oder nicht im PATH)", exc_info=True)
        return False, "ffmpeg nicht gefunden"
    except Exception as e:
        log.error("[MERGE] Unerwarteter Fehler beim Aufruf von ffmpeg", exc_info=True)
        return False, str(e)

    if result.returncode == 0:
        log.info(f"[MERGE] Merge erfolgreich: {output_path}")
        return True, result.stderr

    log.error(f"[MERGE] ffmpeg-Fehler (Exit {result.returncode}): {result.stderr}")
    return False, result.stderr


def is_usable(path: Path | None) -> bool:
    """Whether a take exists and is large enough to be worth mixing."""
    if path is None or not path.exists():
        return False
    return path.stat().st_size >= MIN_USABLE_BYTES
