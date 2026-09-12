"""Which device Windows currently considers the default one.

Moved unchanged out of `main.pyw` (lines 18-23 and 139-224). pycaw is asked for
the *communications* default rather than the multimedia default, because that is
the one a headset takes over when a call starts - and a recording has to follow
the same switch the user hears.
"""

from __future__ import annotations

import time

import sounddevice as sd
import soundcard as sc

from .logging_setup import get_logger

log = get_logger(__name__)

try:
    import comtypes
    from pycaw.utils import AudioUtilities
    PYCAW_AVAILABLE = True
except Exception:
    PYCAW_AVAILABLE = False

EDataFlow_eRender = 0
EDataFlow_eCapture = 1
ERole_eMultimedia = 1
ERole_eCommunications = 2


def get_default_comm_device_name(retries=3, retry_delay=0.05):
    if not PYCAW_AVAILABLE:
        log.warning("pycaw nicht verfuegbar, Geraeteerkennung deaktiviert")
        return None
    for attempt in range(1, retries + 1):
        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            endpoint = enumerator.GetDefaultAudioEndpoint(
                EDataFlow_eCapture, ERole_eCommunications
            )
            device = AudioUtilities.CreateDevice(endpoint)
            name = device.FriendlyName
            if name:
                log.debug(f"pycaw meldet Default-Communications-Geraet: {name}")
                return name
            log.warning(
                f"pycaw lieferte kein FriendlyName fuer Default-Communications-Geraet "
                f"(Property-Store-Fehler, Versuch {attempt}/{retries})"
            )
        except Exception:
            log.error(f"pycaw-Aufruf fehlgeschlagen (GetDefaultAudioEndpoint), Versuch {attempt}/{retries}", exc_info=True)
        if attempt < retries:
            time.sleep(retry_delay)
    return None


def resolve_sounddevice_index(preferred_name):
    if preferred_name:
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if dev["max_input_channels"] > 0 and preferred_name.lower() in str(dev["name"]).lower():
                    log.info(f"Geraet gemappt: '{preferred_name}' -> Index {idx} ({dev['name']})")
                    return idx
            log.warning(f"Kein sounddevice-Match fuer '{preferred_name}', nutze Systemstandard")
        except Exception:
            log.error("Fehler bei query_devices()", exc_info=True)
    try:
        default_idx = sd.default.device[0]
        log.info(f"Nutze PortAudio-Systemstandard, Index {default_idx}")
        return default_idx
    except Exception:
        log.error("Kein Systemstandard-Geraet ermittelbar", exc_info=True)
        return None


def get_default_speaker_device_name(retries=3, retry_delay=0.05):
    if not PYCAW_AVAILABLE:
        log.warning("[SYS] pycaw nicht verfuegbar, Geraeteerkennung deaktiviert")
        return None
    for attempt in range(1, retries + 1):
        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            endpoint = enumerator.GetDefaultAudioEndpoint(
                EDataFlow_eRender, ERole_eCommunications
            )
            device = AudioUtilities.CreateDevice(endpoint)
            name = device.FriendlyName
            if name:
                log.debug(f"[SYS] pycaw meldet Default-Wiedergabegeraet (Kommunikation): {name}")
                return name
            log.warning(
                f"[SYS] pycaw lieferte kein FriendlyName fuer Default-Wiedergabegeraet "
                f"(Property-Store-Fehler, Versuch {attempt}/{retries})"
            )
        except Exception:
            log.error(f"[SYS] pycaw-Aufruf fehlgeschlagen (GetDefaultAudioEndpoint Render), Versuch {attempt}/{retries}", exc_info=True)
        if attempt < retries:
            time.sleep(retry_delay)
    return None


def resolve_soundcard_speaker(preferred_name):
    try:
        if preferred_name:
            for spk in sc.all_speakers():
                if preferred_name.lower() in str(spk.name).lower():
                    log.info(f"[SYS] Geraet gemappt: '{preferred_name}' -> {spk.name}")
                    return spk
            log.warning(f"[SYS] Kein soundcard-Match fuer '{preferred_name}', nutze Systemstandard")
        default_speaker = sc.default_speaker()
        log.info(f"[SYS] Nutze soundcard-Systemstandard: {default_speaker.name}")
        return default_speaker
    except Exception:
        log.error("[SYS] Fehler bei soundcard-Geraeteaufloesung (all_speakers/default_speaker)", exc_info=True)
        return None
