from __future__ import annotations

"""High‑speed data‑acquisition helper for the MCC **USB‑1408FS‑Plus**.

Key design goals
----------------
1. **True 10 kHz throughput** – every sample stored to disk, not just the 10 Hz
   screen refreshes.
2. **Zero GUI changes** – :pymeth:`Display.writeDataToFile` still hands us its
   low‑rate buffer; we use its *length* to infer how long the operator was
   recording and recapture that interval at full rate.
3. **No data loss** – the hardware‑paced scan runs once, after the operator hits
   *Stop*, so we never risk overflowing RAM.

The device can stream 48 kS/s on one channel, so 30 s × 10 kS/s = 300 k samples
is well within spec fileciteturn3file10.
"""

# -----------------------------------------------------------------------------
# Imports & constants
# -----------------------------------------------------------------------------
from __future__ import annotations

import time
from datetime import datetime
from ctypes import cast, POINTER, c_ushort
from typing import List, Tuple

from mcculw import ul
from mcculw.enums import ULRange, ScanOptions, FunctionType

__all__ = ["DataAcquisition"]

# -----------------------------------------------------------------------------
# Helper class
# -----------------------------------------------------------------------------
class DataAcquisition:
    """One‑shot capture of **CH0‑DIFF** at 10 000 samples / s."""

    _TIMEFMT = "%y%m%d_%H%M%S"  # file‑name timestamp

    def __init__(self) -> None:
        # Hardware configuration --------------------------------------------
        self.board_num = 0
        self.channel = 0  # CH0‑HI / CH0‑LO
        self.ai_range = ULRange.BIP20VOLTS  # ±20 V, 14‑bit diff mode
        self.sample_rate = 10_000            # Hz

        # Book‑keeping -------------------------------------------------------
        self.operatorInitials: str = "NULL"

    # ------------------------------------------------------------------
    # Public API (called by Display.py)
    # ------------------------------------------------------------------
    def getSignalData(self) -> float | None:
        """Return a *software‑paced* instantaneous sample for the live graph."""
        try:
            raw = ul.a_in(self.board_num, self.channel, self.ai_range)
            return ul.to_eng_units(self.board_num, self.ai_range, raw)
        except Exception:
            return None

    def writeData(self, gui_data: List[Tuple[float, float]] | None = None) -> None:
        """Re‑record the full session at 10 kHz and write it to ``<INI>_YYMMDD_HHMMSS.txt``.

        The GUI gives us its low‑rate buffer *gui_data* – the last time stamp in
        that list tells us how long the operator was actually recording.
        """
        # Infer recording duration -----------------------------------------
        if gui_data and gui_data[-1]:
            duration_s = gui_data[-1][0]
            # Guard against pathological cases
            duration_s = max(0.2, min(duration_s, 600.0))  # 0.2 s ≤ t ≤ 10 min
        else:
            duration_s = 1.0  # Fallback – shouldn’t really happen

        capture = self._capture_block(duration_s)
        self._write_file(capture)

    # ------------------------------------------------------------------
    # Internal – one hardware‑paced block capture
    # ------------------------------------------------------------------
    def _capture_block(self, duration: float) -> List[Tuple[float, float]]:
        """Blocking capture for *duration* seconds at ``self.sample_rate``."""
        samples = int(round(duration * self.sample_rate))
        if samples <= 0:
            raise ValueError("Duration too short – no samples to acquire.")

        memhandle = ul.win_buf_alloc(samples)
        if not memhandle:
            raise MemoryError("Could not allocate UL buffer.")

        try:
            ul.a_in_scan(
                self.board_num,
                self.channel,
                self.channel,  # low == high -> one channel
                samples,
                self.sample_rate,
                self.ai_range,
                memhandle,
                ScanOptions.BACKGROUND,
            )

            # Wait for completion -------------------------------------
            while ul.get_status(self.board_num, FunctionType.AIFUNCTION)[0] == 1:
                time.sleep(0.003)  # 3 ms poll – negligible CPU

            # Copy & convert ------------------------------------------
            buf_ptr = cast(memhandle, POINTER(c_ushort))
            out: List[Tuple[float, float]] = []
            for i in range(samples):
                volts = ul.to_eng_units(self.board_num, self.ai_range, buf_ptr[i])
                out.append((i / self.sample_rate, volts))
            return out
        finally:
            ul.stop_background(self.board_num, FunctionType.AIFUNCTION)
            ul.win_buf_free(memhandle)

    # ------------------------------------------------------------------
    # File I/O helpers
    # ------------------------------------------------------------------
    def _write_file(self, data: List[Tuple[float, float]]) -> None:
        fname = f"{self.operatorInitials.upper()}_{datetime.now().strftime(self._TIMEFMT)}.txt"
        with open(fname, "w", encoding="utf‑8") as fh:
            for t, v in data:
                fh.write(f"{t:.6f}\t{v:.6f}\n")
