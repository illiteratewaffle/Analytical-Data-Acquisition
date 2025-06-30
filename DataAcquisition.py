import numpy as np
from mcculw import ul
from mcculw.enums import ULRange
from mcculw.ul import ULError
import ctypes as ct
import threading, queue, time
from datetime import datetime


class DataAcquisition:
    blockSize = 100
    samplingFrequency = 10_000  # Hz

    def __init__(self):
        # Board-specific settings (unchanged)
        self.board_num = 0
        self.channel   = 0
        self.ai_range  = ULRange.BIP20VOLTS

        # Pre-allocate one-block buffer
        self._buf = (ct.c_uint16 * self.blockSize)()

        # Run bookkeeping
        self.data: list[tuple[float, float]] = []
        self.operatorInitials: str = "NULL"

        # Threading helpers
        self._queue:   queue.Queue | None = None
        self._thread:  threading.Thread | None = None
        self._running = threading.Event()

    # ------------------------------------------------------------
    # Public control surface
    # ------------------------------------------------------------
    def attach_queue(self, q: queue.Queue) -> None:
        """GUI supplies a queue to receive (t_rel, volts)."""
        self._queue = q

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running.set()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self, join_timeout: float = 1.0) -> None:
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=join_timeout)
            self._thread = None
        self.writeData(self.data)   # auto-save
        self.data = []              # clear for next run

    # ------------------------------------------------------------
    # Background worker — runs in its own thread
    # ------------------------------------------------------------
    def _worker(self) -> None:
        t0 = time.perf_counter()
        while self._running.is_set():
            volts = self.getSignalData()
            if volts is None:
                continue            # skip bad scan, keep running

            t_rel = time.perf_counter() - t0
            epoch1904 = self.getTimeData()
            self.recordData(epoch1904, volts)

            if self._queue:
                try:
                    self._queue.put_nowait((t_rel, volts))
                except queue.Full:      # drop oldest if GUI lags
                    _ = self._queue.get_nowait()
                    self._queue.put_nowait((t_rel, volts))
            # a_in_scan blocks ≈ blockSize/samplingFrequency
            # so no extra sleep is needed

    # ------------------------------------------------------------
    # Low-level helpers (original logic kept intact)
    # ------------------------------------------------------------
    def getSignalData(self) -> float | None:
        try:
            ul.a_in_scan(self.board_num,
                         self.channel, self.channel,
                         self.blockSize, self.samplingFrequency,
                         self.ai_range, self._buf, 0)

            counts = np.ctypeslib.as_array(self._buf).mean()
            return float(ul.to_eng_units(self.board_num, self.ai_range, int(counts)))
        except ULError as e:
            print("UL error:", e.errorcode, e.message)
            return None

    def getTimeData(self) -> float:
        return (datetime.now() - datetime(1904, 1, 1)).total_seconds()

    def recordData(self, epoch1904: float, volts: float) -> None:
        self.data.append((epoch1904, volts))

    # ------------------------------------------------------------
    # File I/O (pattern unchanged)
    # ------------------------------------------------------------
    def writeData(self, data: list[tuple[float, float]]) -> None:
        if not data:
            return
        stamp    = datetime.now().strftime("%y%m%d_%H%M%S")
        initials = (self.operatorInitials or "NULL").upper()
        fname    = f"{initials}_{stamp}"
        with open(fname, "w", encoding="utf-8") as f:
            for epoch, v in data:
                f.write(f"{epoch:.4f}\t{v:.4f}\n")
        print(f"Saved {len(data)} rows to {fname}")
