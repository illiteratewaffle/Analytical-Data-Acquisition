from mcculw import ul
from mcculw.enums import ULRange, ScanOptions, FunctionType
from mcculw.ul import ULError
from mcculw.device_info import DaqDeviceInfo

from ctypes import cast, POINTER, c_ushort
from datetime import datetime
import time

class DataAcquisition:
    def __init__(self):
        self.board_num = 0
        self.channel = 0  # differential CH0 = CH0 HI / CH0 LO
        self.ai_range = ULRange.BIP20VOLTS
        self.operatorInitials = "NULL"

        self.sample_rate = 10000  # Hz
        self.duration = 1         # seconds
        self.samples_per_channel = self.sample_rate * self.duration

    def mainLoop(self) -> None:
        try:
            # Allocate memory for scan
            memhandle = ul.win_buf_alloc(self.samples_per_channel)
            if not memhandle:
                raise RuntimeError("Failed to allocate memory buffer.")

            # Start scan
            ul.a_in_scan(
                self.board_num,
                self.channel,
                self.channel,  # same low and high channel = 1 channel
                self.samples_per_channel,
                self.sample_rate,
                self.ai_range,
                memhandle,
                ScanOptions.BACKGROUND
            )

            # Wait until scan is done
            status = ul.get_status(self.board_num, FunctionType.AIFUNCTION)
            while status[0] == 1:  # 1 = running
                time.sleep(0.01)
                status = ul.get_status(self.board_num, FunctionType.AIFUNCTION)

            # Convert data to list of (time, voltage)
            buffer = cast(memhandle, POINTER(c_ushort))
            data = []
            for i in range(self.samples_per_channel):
                raw_val = buffer[i]
                volts = ul.to_eng_units(self.board_num, self.ai_range, raw_val)
                timestamp = i / self.sample_rate
                data.append((timestamp, volts))

            self.writeData(data)

        finally:
            ul.stop_background(self.board_num, FunctionType.AIFUNCTION)
            ul.win_buf_free(memhandle)

    def writeData(self, data: list) -> None:
        fullFilename = self.operatorInitials.upper() + "_" + self.getSystemTime()
        with open(fullFilename, "w") as dataFile:
            for t, v in data:
                dataFile.write(f"{t:.4f}\t{v:.4f}\n")

    def getSystemTime(self) -> str:
        now = datetime.now()
        return now.strftime("%y%m%d_%H%M%S")
