from __future__ import annotations

"""Data acquisition module – **continuous 10 kHz capture while GUI is running**.

The GUI (``Display.py``) polls `getSignalData()` roughly 10 Hz for the live
plot.  Meanwhile, this class starts a **hardware‑paced** background scan the
moment it is constructed and streams the raw 14‑bit data into a circular buffer
large enough to hold 10 minutes (600 s × 10 kHz = 6 000 000 samples ≈ 12 MiB).
When the operator stops the run, ``writeData()`` spools out everything collected
so far – *no post‑capture re‑measurement*.  The public interface (``getSignalData``
& ``writeData``) is unchanged, so the rest of the code‑base needs no edits.
"""

# ---------------------------------------------------------------------------
# Imports & constants
# ---------------------------------------------------------------------------
import time
from datetime import datetime
from ctypes import cast, POINTER, c_ushort
from typing import List, Tuple

from mcculw import ul
from mcculw.enums import ULRange, ScanOptions, FunctionType

__all__ = ["DataAcquisition"]

# Size of circular buffer (seconds)
_BUFFER_SEC = 600          # 10 min safety margin – 600 s × 10 kHz ≈ 12 MiB RAM
_TIMEFMT = "%y%m%d_%H%M%S"  # YYMMDD_HHMMSS for file names


class DataAcquisition:
    """Continuously grab **CH0‑DIFF** at 10 000 samples / s in the background."""

    def __init__(self) -> None:
        # Device parameters --------------------------------------------------
        self.board_num = 0
        self.channel = 0  # CH0‑HI / CH0‑LO
        self.ai_range = ULRange.BIP20VOLTS
        self.sample_rate = 10_000  # Hz (one‑channel limit 48 kS/s 【5:0†file‑NYum...L23‑L35】)

        # Operator initials – set by GUI before write‑out
        self.operatorInitials: str = "NULL"

        # Allocate circular buffer & kick off continuous scan ---------------
        self._max_samples = int(_BUFFER_SEC * self.sample_rate)
        self._memhandle = ul.win_buf_alloc(self._max_samples)
        if not self._memhandle:
            raise MemoryError("Could not allocate UL buffer.")

        ul.a_in_scan(
            self.board_num,
            self.channel,
            self.channel,
            self._max_samples,
            self.sample_rate,
            self.ai_range,
            self._memhandle,
            ScanOptions.BACKGROUND | ScanOptions.CONTINUOUS,
            )
        # Let the device fill at least one block (32 samples) before first GUI read
        time.sleep(0.005)

    # ------------------------------------------------------------------
    # Public API called by Display.py
    # ------------------------------------------------------------------
    def getSignalData(self) -> float | None:
        """Return an instantaneous *software‑paced* sample for live display."""
        try:
            raw = ul.a_in(self.board_num, self.channel, self.ai_range)
            return ul.to_eng_units(self.board_num, self.ai_range, raw)
        except Exception:
            return None

    def writeData(self, _gui_dump: List[Tuple[float, float]] | None = None) -> None:  # noqa: D401
        """Stop the background scan, dump everything collected, and save to disk."""
        try:
            status, cur_count, cur_index = ul.get_status(self.board_num, FunctionType.AIFUNCTION)
            # cur_count may exceed buffer.  We keep the *latest* _max_samples
            nsamp = min(cur_count, self._max_samples)

            buf_ptr = cast(self._memhandle, POINTER(c_ushort))
            data: List[Tuple[float, float]] = []

            if cur_count <= self._max_samples:
                # No wrap‑around – samples are in order 0 … nsamp‑1
                for i in range(nsamp):
                    volts = ul.to_eng_units(self.board_num, self.ai_range, buf_ptr[i])
                    data.append((i / self.sample_rate, volts))
            else:
                # Buffer wrapped – start after cur_index for chronological order
                start = (cur_index + 1) % self._max_samples
                for i in range(nsamp):
                    idx = (start + i) % self._max_samples
                    volts = ul.to_eng_units(self.board_num, self.ai_range, buf_ptr[idx])
                    t = (cur_count - nsamp + i) / self.sample_rate  # true time stamp
                    data.append((t, volts))

            self._write_file(data)
        finally:
            ul.stop_background(self.board_num, FunctionType.AIFUNCTION)
            ul.win_buf_free(self._memhandle)
            self._memhandle = None  # help GC

    # ------------------------------------------------------------------
    # File helper
    # ------------------------------------------------------------------
    def _write_file(self, data: List[Tuple[float, float]]) -> None:
        fname = f"{self.operatorInitials.upper()}_{datetime.now().strftime(_TIMEFMT)}.txt"
        with open(fname, "w", encoding="utf‑8") as fh:
            for t, v in data:
                fh.write(f"{t:.6f}\t{v:.6f}\n")

    # ------------------------------------------------------------------
    # Destructor – belt & suspenders
    # ------------------------------------------------------------------
    def __del__(self):
        try:
            if self._memhandle:
                ul.stop_background(self.board_num, FunctionType.AIFUNCTION)
                ul.win_buf_free(self._memhandle)
        except Exception:
            pass
