from mcculw import ul
from mcculw.enums import ULRange, ScanOptions, FunctionType
from ctypes import cast, POINTER, c_ushort
from datetime import datetime
import time


class DataAcquisition:
    """High‑speed (10 kHz) data‑acquisition helper.

    * Provides a simple :py:meth:`getSignalData` call for GUI polling at any rate.
    * Offers :py:meth:`mainLoop` for burst captures at *exactly* ``sample_rate``
      (default 10 000 Hz) while still remaining compatible with the rest of the
      codebase (``Display.py`` expects :py:meth:`getSignalData`).
    """

    def __init__(
            self,
            board_num: int = 0,
            channel: int = 0,
            ai_range: ULRange = ULRange.BIP20VOLTS,
            sample_rate: int = 10_000,
    ) -> None:
        self.board_num = board_num
        self.channel = channel  # differential CH0 = CH0 HI / CH0 LO
        self.ai_range = ai_range

        self.operatorInitials: str = "NULL"

        # ---- Acquisition parameters ------------------------------------------------
        self.sample_rate = int(sample_rate)  # **exactly** 10 000 Hz by default
        self.duration = 1  # seconds for block capture
        self._update_sample_count()

    # ---------------------------------------------------------------------------
    # Public helpers used elsewhere in codebase
    # ---------------------------------------------------------------------------

    def getSignalData(self) -> float:
        """Return the latest single‑point voltage reading (in volts).

        This call is *blocking* for only a few micro‑seconds (single A/D
        conversion) and is intended for low‑rate GUI updates in ``Display.py``.
        """
        raw_val = ul.a_in(self.board_num, self.channel, self.ai_range)
        return ul.to_eng_units(self.board_num, self.ai_range, raw_val)

    # ---------------------------------------------------------------------------
    # Optional block‑capture API (not currently used by the GUI but kept for
    #   compatibility with previous scripts).
    # ---------------------------------------------------------------------------

    def setSampleRate(self, sample_rate: int) -> None:
        """Change the sampling rate (Hz) *before* calling :py:meth:`mainLoop`."""
        self.sample_rate = int(sample_rate)
        self._update_sample_count()

    def setDuration(self, seconds: float) -> None:
        """Change the capture duration for :py:meth:`mainLoop`."""
        self.duration = float(seconds)
        self._update_sample_count()

    def mainLoop(self) -> None:
        """Acquire a *block* of data at 10 kHz and immediately write to disk."""
        memhandle = ul.win_buf_alloc(self.samples_per_channel)
        if not memhandle:
            raise RuntimeError("Failed to allocate memory buffer.")

        try:
            # Kick‑off hardware‑paced scan (background = non‑blocking).
            ul.a_in_scan(
                self.board_num,
                self.channel,
                self.channel,  # low chan == high chan → single channel
                self.samples_per_channel,
                self.sample_rate,
                self.ai_range,
                memhandle,
                ScanOptions.BACKGROUND,
            )

            # Busy‑wait (few ms) until scan is complete.
            while True:
                status, _cur_count, _cur_index = ul.get_status(
                    self.board_num, FunctionType.AIFUNCTION
                )
                if status == 0:  # idle
                    break
                time.sleep(0.01)

            # Copy data into Python list with timestamps.
            buffer = cast(memhandle, POINTER(c_ushort))
            data = [
                (
                    i / self.sample_rate,
                    ul.to_eng_units(self.board_num, self.ai_range, buffer[i]),
                )
                for i in range(self.samples_per_channel)
            ]

            # Persist to disk in TSV format.
            self.writeData(data)
        finally:
            ul.stop_background(self.board_num, FunctionType.AIFUNCTION)
            ul.win_buf_free(memhandle)

    # ---------------------------------------------------------------------------
    # Utility internals
    # ---------------------------------------------------------------------------

    def writeData(self, data: list[tuple[float, float]]) -> None:
        """Write ``(time, voltage)`` pairs to a timestamped TSV file."""
        filename = f"{self.operatorInitials.upper()}_{self._timestamp()}.txt"
        with open(filename, "w", encoding="utf-8") as fp:
            for t, v in data:
                fp.write(f"{t:.4f}\t{v:.4f}\n")

    def _update_sample_count(self) -> None:
        self.samples_per_channel = int(self.sample_rate * self.duration)

    @staticmethod
    def _timestamp() -> str:
        """Current system time formatted as YYMMDD_HHMMSS."""
        return datetime.now().strftime("%y%m%d_%H%M%S")
