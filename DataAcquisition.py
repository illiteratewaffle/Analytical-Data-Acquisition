import numpy as np
from mcculw import ul
from mcculw.enums import ULRange, ScanOptions
from mcculw.ul import ULError
from mcculw.device_info import DaqDeviceInfo
import ctypes as ct

import time
from datetime import datetime

def _create_float_buffer(n: int):
    """
    Return a ctypes float array of length n.
    Uses ul.create_float_buffer() when available (UL ≥ 1.0.1),
    else falls back to a plain ctypes array. No dependencies.
    """
    return ul.create_float_buffer(n) if hasattr(ul, "create_float_buffer") \
           else (ct.c_float * n)()

class DataAcquisition:
    blockSize = 1
    samplingFrequency = 10000 #Hz

    def __init__(self):
        # board number: found in InstaCal
        self.board_num = 0

        # channel/range: see ports in MCCDAQ manual
        self.channel = 0
        self.ai_range = ULRange.BIP20VOLTS  # "ai" = analog input

        self.data = []
        self.startTime = time.perf_counter()

        self.operatorInitials = "NULL"

        #allocate buffer for 1 block
        self._buf = (ct.c_uint16 * self.blockSize)()

    def mainLoop(self) -> None:
        self.startTime = time.perf_counter()
        
        # todo: make it run for x amount of time
        #while (1 == 1):
        for i in range(1):
            signalValue = self.getSignalData()
            timeValue = self.getTimeData(self.startTime)
            self.recordData(timeValue, signalValue)

        self.writeData(self.data)


    def getSignalData(self) -> (float | None):
        try:
            ul.a_in_scan(self.board_num,
                         self.channel,
                         self.channel,
                         self.blockSize,
                         self.samplingFrequency,
                         self.ai_range,
                         self._buf,
                         0)

            # Convert ctypes buffer. NumPy array for fast math
            countsArr = np.ctypeslib.as_array(self._buf)
            meanCounts = int(countsArr.mean())
            meanVolts = ul.to_eng_units(self.board_num, self.ai_range, meanCounts)
            return float(meanVolts)

        except ULError as e:  # Display the error (if needed)
            print("A UL error occurred. Code: " + str(e.errorcode) + " Message: " + e.message)

            return None

    def getTimeData(self) -> float:
        now = datetime.now()
        theBeginning = datetime(1904, 1, 1, 0, 0, 0)
        seconds_since_1904 = (now - theBeginning).total_seconds()
        return seconds_since_1904

    def recordData(self, time: float, signal: float) -> None:
        self.data.append([time, signal])

    def writeData(self, data: list[tuple[float, float]]) -> None:
        if not data:
            return

        # Build filename: <INITIALS>_YYMMDD_HHMMSS
        timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
        initials  = (self.operatorInitials or "NULL").upper()
        fname     = f"{initials}_{timestamp}"

        with open(fname, "w", encoding="utf-8") as f:
            for epoch, mean_v in data: # iterate over *argument* list
                f.write(f"{epoch:.4f}\t{mean_v:.4f}\n")

        print(f"Saved {len(data)} rows : {fname}")

    def getSystemTime(self) -> str:
        now = datetime.now()
        formatted = now.strftime("%y%m%d_%H%M%S")

        return formatted