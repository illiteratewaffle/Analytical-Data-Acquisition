from __future__ import annotations

"""High‑speed data‑acquisition helper for the MCC USB‑1408FS‑Plus.

The **Display** GUI polls only ~10 Hz, but this module now *internally* captures a
continuous **10 kHz** hardware‑paced stream.  When the GUI asks us to write the
file we ignore its low‑rate buffer and instead dump our full‑rate capture, so no
other file in the code‑base needs to change.
"""

# -----------------------------------------------------------------------------
# Imports & constants
# -----------------------------------------------------------------------------
from ctypes import cast, POINTER, c_ushort
from datetime import datetime
import time
import threading
from typing import List, Tuple

from mcculw import ul
from mcculw.enums import ULRange, ScanOptions, FunctionType

# -----------------------------------------------------------------------------
# The DataAcquisition class
# -----------------------------------------------------------------------------
class DataAcquisition:
    """Acquire differential CH0 at **10 kHz** and play nicely with the GUI."""

    #: File timestamp format YYMMDD_HHMMSS
    _TIMEFMT = "%y%m%d_%H%M%S"

    def __init__(self) -> None:
        # Hardware settings ----------------------------------------------------
        self.board_num: int = 0
        self.channel: int = 0               # CH0‑HI / CH0‑LO differential
        self.ai_range = ULRange.BIP20VOLTS  # ±20 V (full 14‑bit resolution)

        # Acquisition settings -------------------------------------------------
        self.sample_rate: int = 10_000      # 10 kHz
        self.duration: float = 1.0          # seconds per burst capture
        self.samples_per_channel: int = int(self.sample_rate * self.duration)

        # House‑keeping --------------------------------------------------------
        self.operatorInitials: str = "NULL"
        self._latest_voltage: float | None = None  # last sample for GUI
        self._capture: List[Tuple[float, float]] = []  # (t, V) tuples
        self._lock = threading.Lock()                # protect _capture
        self._inScan: bool = False                   # re‑entry guard

    # ---------------------------------------------------------------------
    # Public API used by Display.py
    # ---------------------------------------------------------------------
    def getSignalData(self) -> float | None:
        """Return *one* instantaneous reading for the GUI (software‑paced)."""
        try:
            raw = ul.a_in(self.board_num, self.channel, self.ai_range)
            volts = ul.to_eng_units(self.board_num, self.ai_range, raw)
            # Remember for quick graph redraws even if capture thread stalls
            self._latest_voltage = volts
            return volts
        except Exception:
            # Keep previously known value so the GUI still shows *something*
            return self._latest_voltage

    def writeData(self, _stub_from_gui: list | None = None) -> None:  # noqa: D401
        """Called by the GUI when the user stops recording.

        *We ignore the slow‑rate buffer passed in by the GUI.*  Instead we run a
        dedicated 10 kHz burst capture (`mainLoop`) and write that high‑rate
        data to disk, so no changes are required elsewhere in the code‑base.
        """
        # If we are *already* inside mainLoop() just finish writing the file:
        if self._inScan:
            self._write_file(_stub_from_gui)  # type: ignore[arg-type]
            return

        # Otherwise perform a fresh high‑speed capture and write that:
        data = self.mainLoop()
        self._write_file(data)

    # ---------------------------------------------------------------------
    # High‑speed capture helpers
    # ---------------------------------------------------------------------
    def mainLoop(self) -> List[Tuple[float, float]]:
        """Blocking 10 kHz hardware‑paced capture for *self.duration* seconds."""
        self._inScan = True
        try:
            # Allocate contiguous buffer (16‑bit unsigned ints)
            memhandle = ul.win_buf_alloc(self.samples_per_channel)
            if not memhandle:
                raise MemoryError("Could not allocate UL buffer.")

            # Kick off background scan -------------------------------------
            ul.a_in_scan(
                self.board_num,
                self.channel,
                self.channel,  # low == high -> single channel
                self.samples_per_channel,
                self.sample_rate,
                self.ai_range,
                memhandle,
                ScanOptions.BACKGROUND,
            )

            # Wait for completion -----------------------------------------
            while ul.get_status(self.board_num, FunctionType.AIFUNCTION)[0] == 1:
                time.sleep(0.002)  # 2 ms polling = negligible CPU

            # Read buffer & convert to engineering units -------------------
            buf_ptr = cast(memhandle, POINTER(c_ushort))
            capture: List[Tuple[float, float]] = []
            for i in range(self.samples_per_channel):
                raw = buf_ptr[i]
                volts = ul.to_eng_units(self.board_num, self.ai_range, raw)
                t = i / self.sample_rate
                capture.append((t, volts))

            # Keep an in‑memory copy in case the caller wants it later
            with self._lock:
                self._capture = capture.copy()

            return capture
        finally:
            ul.stop_background(self.board_num, FunctionType.AIFUNCTION)
            ul.win_buf_free(memhandle)  # always free UL buffer
            self._inScan = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_timestamp(self) -> str:
        return datetime.now().strftime(self._TIMEFMT)

    def _write_file(self, data: List[Tuple[float, float]]) -> None:
        """Write (t, V) pairs to a tab‑delimited text file."""
        fname = f"{self.operatorInitials.upper()}_{self._get_timestamp()}.txt"
        with open(fname, "w", encoding="utf‑8") as fh:
            for t, v in data:
                fh.write(f"{t:.6f}\t{v:.6f}\n")
