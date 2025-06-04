from __future__ import annotations

"""High‑rate DAQ helper — **records at 10 kHz *while* the GUI runs**.

This replaces the original one‑shot, 1‑s scan with a **continuous hardware‑paced
stream**.

Behaviour summary
=================
* **Automatic scan start** — a 10 kHz scan begins the moment the object is
  constructed (Display instantiates us before it starts its timer).
* **Fast live value** — :py:meth:`getSignalData` still returns a single
  software‑paced reading for the on‑screen read‑out (no GUI changes).
* **File save** — when Display calls :py:meth:`writeData(...)` we *stop* the
  scan, pull all acquired samples out of the ring buffer (properly handling any
  wrap‑around) and write them to disk at full resolution.  The low‑rate list
  that Display passes in is accepted but ignored.

Implementation notes
--------------------
* We allocate a **circular buffer** sized for 10 minutes at 10 kHz ≈ 6 000 000
  samples (12 MiB).  Plenty of margin above the GUI’s default 30 s recording.
* The MCC **USB‑1408FS‑Plus** delivers blocks of 32 samples over USB; the
  Measurement Computing driver (``mcculw``) updates ``cur_index`` to point to
  the *most‑recent* element in the buffer.
* Timestamps in the output file are referenced to the *first* sample kept —
  they therefore span 0 → <elapsed runtime> and align with the user’s
  expectation that time 0 ≈ start of recording.
"""

# ---------------------------------------------------------------------------
# Imports & constants
# ---------------------------------------------------------------------------
from ctypes import cast, POINTER, c_ushort
from datetime import datetime
from typing import List, Tuple, Any

from mcculw import ul
from mcculw.enums import ULRange, ScanOptions, FunctionType

import time

__all__ = ["DataAcquisition"]

_SAMPLE_RATE = 10_000  # Hz – one‑channel limit is 48 kS/s fileciteturn7file7L23-L37
_BUFFER_SEC = 600      # 10 minutes safety margin → 6e6 samples ≈ 12 MiB
_TIMEFMT = "%y%m%d_%H%M%S"  # file‑name timestamp


class DataAcquisition:
    """Continuously stream CH0‑DIFF at 10 kHz into a ring buffer."""

    # ------------------------------------------------------------------
    # Construction – allocate buffer & start scan
    # ------------------------------------------------------------------
    def __init__(self) -> None:
        self.board_num = 0
        self.channel = 0
        self.ai_range = ULRange.BIP20VOLTS
        self.operatorInitials: str = "NULL"

        self._max_samples = int(_BUFFER_SEC * _SAMPLE_RATE)
        self._memhandle = ul.win_buf_alloc(self._max_samples)
        if not self._memhandle:
            raise MemoryError("mcculw: unable to allocate DAQ buffer")

        # Kick off hardware‑paced *continuous* scan
        ul.a_in_scan(
            self.board_num,
            self.channel,
            self.channel,                       # one channel only
            self._max_samples,                  # buffer size – ignored in CONTINUOUS mode but required
            _SAMPLE_RATE,
            self.ai_range,
            self._memhandle,
            ScanOptions.BACKGROUND | ScanOptions.CONTINUOUS,
            )
        # Give driver time to DMA the first block (32 samples)
        time.sleep(0.005)

    # ------------------------------------------------------------------
    # GUI live‑value helper
    # ------------------------------------------------------------------
    def getSignalData(self) -> float | None:
        """Return an instantaneous software‑paced sample for the live read‑out."""
        try:
            raw = ul.a_in(self.board_num, self.channel, self.ai_range)
            return ul.to_eng_units(self.board_num, self.ai_range, raw)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # File‑write entry‑point (Display passes in its low‑rate list – ignored)
    # ------------------------------------------------------------------
    def writeData(self, *_ignored: Any) -> None:  # noqa: D401 – keep Display signature
        """Stop acquisition, dump full‑rate data to ``<INITIALS>_YYMMDD_HHMMSS.txt``."""
        try:
            # Freeze sample count
            status, cur_count, cur_index = ul.get_status(self.board_num, FunctionType.AIFUNCTION)
            nsamp = min(cur_count, self._max_samples)

            # Stop the device so no new data arrive while we copy
            ul.stop_background(self.board_num, FunctionType.AIFUNCTION)

            buf_ptr = cast(self._memhandle, POINTER(c_ushort))
            data: List[Tuple[float, float]] = []

            if cur_count < self._max_samples:
                # No wrap‑around – samples are already chronological
                first = 0
            else:
                # Buffer wrapped – earliest sample is *next* after cur_index
                first = (cur_index + 1) % self._max_samples

            for i in range(nsamp):
                idx = (first + i) % self._max_samples
                volts = ul.to_eng_units(self.board_num, self.ai_range, buf_ptr[idx])
                t = i / _SAMPLE_RATE  # 0‑based timeline aligned to first kept sample
                data.append((t, volts))

            self._write_file(data)
        finally:
            ul.win_buf_free(self._memhandle)
            self._memhandle = None

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------
    def _write_file(self, data: List[Tuple[float, float]]) -> None:
        fname = f"{self.operatorInitials.upper()}_{datetime.now().strftime(_TIMEFMT)}.txt"
        with open(fname, "w", encoding="utf‑8") as fh:
            for t, v in data:
                fh.write(f"{t:.6f}\t{v:.6f}\n")

    # ------------------------------------------------------------------
    # Destructor – make *sure* the board stops
    # ------------------------------------------------------------------
    def __del__(self):
        try:
            if self._memhandle:
                ul.stop_background(self.board_num, FunctionType.AIFUNCTION)
                ul.win_buf_free(self._memhandle)
        except Exception:
            pass
