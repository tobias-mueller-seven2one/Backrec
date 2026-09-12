"""Backrec: records microphone and system audio and merges both into one file.

The package deliberately imports nothing at package level. `cli` has to stay
importable on a machine where customtkinter or pycaw are missing, because that
is exactly the situation `doctor` is there to report on.
"""

from __future__ import annotations
