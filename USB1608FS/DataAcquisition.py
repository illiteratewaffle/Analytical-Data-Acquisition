# DataAcquisition.py
import numpy as np
from mcculw import ul
from mcculw.enums import ULRange
from mcculw.ul import ULError
import ctypes as ct
import threading, queue, time
from datetime import datetime

from Settings import settings


class DataAcquisition:
    blockSize = 100
    samplingFrequency = 10_000  # Hz

    def __init__(self):
        # Board-specific settings (updated to use settings)
        self.board_num = settings.ai_board_number
        self.channel = settings.ai_channel
        self.ai_range = ULRange.BIP10VOLTS
        self._hardware_available = False

        try:
            # Try to access the board to verify it exists
            ul.get_board_name(self.board_num)
            self._hardware_available = True
        except ULError:
            print(f"Warning: Analog input board {self.board_num} not found. Running in simulation mode.")
            self._hardware_available = False

        # Pre-allocate one-block buffer
        self._buf = (ct.c_uint16 * self.blockSize)()

        # Run bookkeeping
        self.data: list[tuple[float, float]] = []

        # initial file name
        self.filename = None

        # Threading helpers
        self._queue: queue.Queue | None = None
        self._thread: threading.Thread | None = None
        self._running = threading.Event()

    def set_filename(self, filename):
        self.filename = filename

    # Public control surface
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
        self.writeData(self.data)  # auto-save
        self.data = []  # clear for next run

    # Background worker — runs in its own thread
    def _worker(self) -> None:
        t0 = time.perf_counter()
        while self._running.is_set():
            volts = self.getSignalData()
            if volts is None:
                continue  # skip bad scan, keep running

            t_rel = time.perf_counter() - t0
            epoch1904 = self.getTimeData()
            self.recordData(epoch1904, volts)

            if self._queue:
                try:
                    self._queue.put_nowait((t_rel, volts))
                except queue.Full:  # drop oldest if GUI lags
                    _ = self._queue.get_nowait()
                    self._queue.put_nowait((t_rel, volts))
            # a_in_scan blocks ≈ blockSize/samplingFrequency
            # so no extra sleep is needed

    # Low-level helpers
    def getSignalData(self) -> float | None:
        if not self._hardware_available:
            # Simulate a sine wave when hardware isn't available
            return 2.5 + 2.5 * np.sin(time.perf_counter() * 2 * np.pi * 0.1)

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

    # File I/O
    def writeData(self, data: list[tuple[float, float]]) -> None:
        if not data or not self.filename:
            return

        with open(self.filename, "w", encoding="utf-8") as f:
            for epoch, v in data:
                #format: "[time since Jan 1st 1904] TAB [Signal up to 4 decimal places]"
                f.write(f"{epoch:.4f}\t{v:.4f}\n")
        print(f"Saved {len(data)} rows to {self.filename}")